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
from src.help_overlay import HelpOverlay
from src.personal_best_manager import PersonalBestManager
from utils.path_helper import resource_path
from src.rubiks_cube import RubiksCube

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
        
        try:
            pygame.mixer.init()
            volume_level = self.settings.settings["volume"] / 100
            pygame.mixer.music.set_volume(volume_level)
            pygame.mixer.music.load(self.playlist[self.current_song])
            pygame.mixer.music.play()
            pygame.mixer.music.set_endevent(self.MUSIC_END_EVENT)
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
        
        # Initialize menu
        self.menu = Menu(self.width, self.height)
        self.menu.set_game_instance(self)
        
        # Initialize personal best manager
        self.personal_best_manager = PersonalBestManager()
        
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
        
        # Initialize help overlay
        self.help_overlay = HelpOverlay(self.width, self.height)
        self.help_overlay.set_game_callback(self.handle_overlay_callback)
        
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
        
        # Banner notification system
        self.banner_active = False
        self.banner_text = ""
        self.banner_start_time = 0
        self.banner_duration = 5.0  # 3 seconds total display time
        self.banner_fade_duration = 0.2  # 0.5 seconds for fade in/out
        self.banner_alpha = 0.0
        
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
        print("  Ctrl+B: Toggle debug mode")

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
                
            if hasattr(self, 'help_overlay'):
                self.help_overlay.update_dimensions(self.width, self.height)
            
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
                
            if hasattr(self, 'help_overlay'):
                self.help_overlay.update_dimensions(self.width, self.height)
    
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
                
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    # Check if help overlay is active first
                    if hasattr(self, 'help_overlay') and self.help_overlay.active:
                        self.help_overlay.toggle()
                    # Don't allow closing results window with ESC - user must choose an option
                    elif not self.results_window.active:
                        # Only allow ESC to toggle menu if difficulty has been changed at least once
                        if self.difficulty_change_count >= 1:
                            menu_was_active = self.menu.is_active()
                            self.menu.toggle()
                            if menu_was_active:
                                pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_ARROW)
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
        
            elif self.menu.handle_event(event):
                continue
                
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                # Handle help overlay clicks first (works even when menu/results are active)
                if self.help_overlay.handle_click(event.pos):
                    continue
                    
                # Then handle other mouse interactions only if menu/results not active
                if not self.menu.is_active() and not self.results_window.active:
                    # Left mouse button - camera rotation
                    self.mouse_rotating = True
                    self.prev_mouse_x, self.prev_mouse_y = event.pos
                    self.auto_rotate = False
                    self.debug_print(f"Mouse rotation started at {event.pos}")
                    
            elif not self.menu.is_active() and not self.results_window.active and event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 3:  # Right mouse button - cube moves
                    self.mouse_cube_moving = True
                    self.mouse_interaction.start_drag(event.pos)
                    self.auto_rotate = False
                    self.debug_print(f"Mouse cube interaction started at {event.pos}")
                    
            elif event.type == pygame.MOUSEBUTTONUP:
                if event.button == 1 and not self.menu.is_active() and not self.results_window.active:
                    self.mouse_rotating = False
                    self.debug_print("Mouse rotation ended")
                elif event.button == 3 and not self.menu.is_active() and not self.results_window.active:
                    self.mouse_cube_moving = False
                    self.mouse_interaction.end_drag()
                    self.debug_print("Mouse cube interaction ended")
                
            elif not self.menu.is_active() and not self.results_window.active and event.type == pygame.MOUSEMOTION:
                # Handle camera rotation with left mouse button
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
                
                # Handle cube moves with right mouse button
                elif self.mouse_cube_moving:
                    detected_move = self.mouse_interaction.update_drag(event.pos)
                    if detected_move:
                        self.debug_print(f"🔥 Revolutionary move detected: {detected_move}")
                        # Show revolutionary debug info
                        debug_info = self.mouse_interaction.get_debug_info()
                        self.debug_print(f"   Face: {debug_info['detected_face']}, Zone: {debug_info['detected_zone']}")
                        self.execute_cube_move(detected_move)
                
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
            self.results_window.update()
            
        # Update help overlay animation
        if hasattr(self, 'help_overlay'):
            self.help_overlay.update()
            
        # Update sound manager music fade
        if hasattr(self, 'sound_manager'):
            self.sound_manager.update_music_fade()
        
        # Update cursor based on menu/results window state
        mouse_pos = pygame.mouse.get_pos()
        if hasattr(self, 'menu') and self.menu.is_active():
            self.menu.update_cursor(mouse_pos)
        elif hasattr(self, 'results_window') and self.results_window.active:
            self.results_window.update_cursor(mouse_pos)
        else:
            # Update help overlay hover state and set appropriate cursor
            if hasattr(self, 'help_overlay'):
                hover_changed = self.help_overlay.update_hover(mouse_pos)
                if self.help_overlay.is_hovering_help or self.help_overlay.is_hovering_menu:
                    pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_HAND)
                else:
                    pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_ARROW)
            else:
                # Default cursor when in game
                pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_ARROW)
        
        # Update banner animation
        self.update_banner()
        
        # Update animated scrambling
        self.update_animated_scramble()
        
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
        
        # Note: We no longer reset game_started when menu is opened
        # This allows the user to pause and resume their current game
        
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
                if self.renderer.rubiks_cube.is_solved():
                    self.cube_solved = True
                    solve_time = time.time() - self.start_time
                    tps = self.move_counter / solve_time if solve_time > 0 else 0
                    
                    # Get current difficulty to determine if we should show results
                    current_difficulty = self.menu.get_selected_difficulty()
                    
                    # Only show win messages and results window if not in freeplay mode
                    if current_difficulty != "freeplay":
                        # Print to terminal for debug purposes
                        print(f"🎉 CUBE SOLVED! 🎉")
                        
                        # Show results window
                        self.results_window.show_results(self.move_counter, solve_time, tps, current_difficulty)
            
            # Update animation state
            self.renderer._last_animation_state = self.renderer.is_animating
    
    def render(self):
        # Render 3D cube
        self.renderer.render_frame()
        
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
    
        # Render help overlay efficiently - only when visible and not blocked
        if (hasattr(self, 'help_overlay') and 
            not self.menu.is_active() and 
            not self.results_window.active and
            (self.help_overlay.active or self.help_overlay.current_alpha > 0.01)):
            
            # Only create surface when help panel is actually visible
            help_surface = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
            self.help_overlay.draw(help_surface)
            
            # Convert pygame surface to OpenGL texture
            texture_data = pygame.image.tostring(help_surface, 'RGBA', True)
            
            glRasterPos2f(0, self.height)
            glPixelZoom(1, 1)  # Flip vertically
            glDrawPixels(self.width, self.height, GL_RGBA, GL_UNSIGNED_BYTE, texture_data)
        
        # Render just the buttons when panel is not visible (much more efficient)
        elif (hasattr(self, 'help_overlay') and 
              not self.menu.is_active() and 
              not self.results_window.active):
            
            # Calculate total area needed for both buttons
            button_margin = 10
            total_width = (self.help_overlay.help_button_size * 2) + self.help_overlay.button_spacing + (button_margin * 2)
            button_area_height = self.help_overlay.help_button_size + (button_margin * 2)
            button_surface = pygame.Surface((total_width, button_area_height), pygame.SRCALPHA)
            
            # Draw help button (left)
            help_x = button_margin
            help_y = button_margin
            if self.help_overlay.is_hovering_help:
                button_surface.blit(self.help_overlay.help_button_surface_hover, (help_x, help_y))
            else:
                button_surface.blit(self.help_overlay.help_button_surface, (help_x, help_y))
            
            # Draw menu button (right)
            menu_x = button_margin + self.help_overlay.help_button_size + self.help_overlay.button_spacing
            menu_y = button_margin
            if self.help_overlay.is_hovering_menu:
                button_surface.blit(self.help_overlay.menu_button_surface_hover, (menu_x, menu_y))
            else:
                button_surface.blit(self.help_overlay.menu_button_surface, (menu_x, menu_y))
            
            # Convert surface to OpenGL
            texture_data = pygame.image.tostring(button_surface, 'RGBA', True)
            
            # Position correctly (align with help button position, which is now leftmost)
            buttons_x = self.help_overlay.help_button_rect.x - button_margin
            buttons_y = self.help_overlay.help_button_rect.y - button_margin
            
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
            
            # Add a semi-transparent background for better readability
            text_width, text_height = text_surface.get_size()
            bg_surface = pygame.Surface((text_width + 20, text_height + 10), pygame.SRCALPHA)
            bg_surface.fill((0, 0, 0, 128))  # Semi-transparent black background
            
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
            
            # Add moves counter
            text_lines.append(f"Moves: {self.move_counter}")
            
            # Check if timer is enabled for current game mode
            current_difficulty = self.menu.get_selected_difficulty()
            game_mode_config = self.menu.get_game_mode_config(current_difficulty)
            timer_enabled = game_mode_config.get("timer_enabled", True)  # Default to True for compatibility
            
            # Add timer only if enabled
            if timer_enabled:
                if self.start_time is not None:
                    elapsed = time.time() - self.start_time
                    minutes = int(elapsed // 60)
                    seconds = int(elapsed % 60)
                    text_lines.append(f"Time: {minutes:02d}:{seconds:02d}")
                else:
                    text_lines.append("Time: 00:00")
            
            # Calculate dimensions for background
            text_surfaces = []
            max_width = 0
            total_height = 0
            line_height = 0
            
            for line in text_lines:
                text_surface = self._stats_font.render(line, True, (255, 255, 255))
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
            
            # Create background surface with alpha
            bg_surface = pygame.Surface((bg_width, bg_height), pygame.SRCALPHA)
            bg_alpha = int(128 * alpha)  # Apply alpha to background
            bg_surface.fill((0, 0, 0, bg_alpha))  # Semi-transparent black background
            
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

            # Create banner surface with alpha
            banner_surface = pygame.Surface((banner_width, banner_height), pygame.SRCALPHA)
            
            # Banner background (semi-transparent black)
            background_alpha = int(180 * self.banner_alpha)  # 180 max alpha for background
            banner_surface.fill((0, 0, 0, background_alpha))
            
            # Banner border (subtle white border)
            border_alpha = int(100 * self.banner_alpha)
            pygame.draw.rect(banner_surface, (255, 255, 255, border_alpha), 
                           (0, 0, banner_width, banner_height), width=2)
            
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

    def execute_cube_move(self, move_notation):
        """Execute a Rubik's cube move with animation"""
        # Don't allow new moves while animating
        if self.renderer.is_animating:
            return
        
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
            else:
                self.debug_print(f"Scramble move: {move_notation} (animating)")
    
    def undo_move(self):
        """Undo the last move"""
        if self.renderer.rubiks_cube.undo_last_move():
            # Play random cube movement sound for undo
            self.sound_manager.play_random_cube_sound()
            
            self.renderer.update_cube_colors()
            self.move_counter = max(0, self.move_counter - 1)
            self.debug_print(f"Move undone. Move count: {self.move_counter}")
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
        
        if difficulty == "freeplay":
            # Free play: Keep cube solved (no scrambling)
            self.debug_print("Free play mode: Cube ready for practice!")
        elif difficulty == "easy":
            # Easy: 5 moves scramble
            self.animated_scramble_cube(1)
            self.debug_print("Easy mode: Scramble with 1 move!")
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
                info_lines.append("🎉 SOLVED! 🎉")
            
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
            fallback_width, fallback_height = 1024, 768
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
                
            if hasattr(self, 'help_overlay'):
                self.help_overlay.update_dimensions(fallback_width, fallback_height)
            
            print(f"Successfully restored to fallback resolution: {fallback_width}x{fallback_height}")
        except Exception as e:
            print(f"Critical error in fallback resolution: {e}")
            # Nothing more we can do at this point
            self.running = False